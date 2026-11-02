"""Small grayscale CNN used on the ESP32 and in training.

The on-device loops in gesture_classifier.cpp follow forward_loops().
"""

import numpy as np

FILTERS = (16, 32, 48)
INPUT_SIZE = 64
CLASSES = 5


def conv_s2(x, weight, bias):
    """Valid 3x3 stride-2 convolution with ReLU. x is NCHW."""
    n, channels, height, width = x.shape
    out_c = weight.shape[0]
    out_h = (height - 3) // 2 + 1
    out_w = (width - 3) // 2 + 1
    acc = np.zeros((n, out_c, out_h, out_w), dtype=np.float32)
    for ky in range(3):
        for kx in range(3):
            patch = x[:, :, ky : ky + out_h * 2 : 2, kx : kx + out_w * 2 : 2]
            acc += np.einsum("oi,nihw->nohw", weight[:, :, ky, kx], patch, optimize=True)
    acc += bias.reshape(1, -1, 1, 1)
    return np.maximum(acc, 0.0), acc


def conv_s2_backward(x, weight, grad_out):
    n, channels, height, width = x.shape
    out_h = grad_out.shape[2]
    out_w = grad_out.shape[3]
    grad_x = np.zeros_like(x)
    grad_w = np.zeros_like(weight)
    grad_b = grad_out.sum(axis=(0, 2, 3))
    for ky in range(3):
        for kx in range(3):
            patch = x[:, :, ky : ky + out_h * 2 : 2, kx : kx + out_w * 2 : 2]
            grad_w[:, :, ky, kx] = np.einsum("nihw,nohw->oi", patch, grad_out, optimize=True)
            grad_patch = np.einsum("oi,nohw->nihw", weight[:, :, ky, kx], grad_out, optimize=True)
            grad_x[:, :, ky : ky + out_h * 2 : 2, kx : kx + out_w * 2 : 2] += grad_patch
    return grad_x, grad_w, grad_b


def quadrant_pool(x):
    """Average the four quadrants. Output is N, 4C, top-left first, row-major."""
    _, channels, height, width = x.shape
    mid_h, mid_w = height // 2, width // 2
    regions = [
        x[:, :, :mid_h, :mid_w],
        x[:, :, :mid_h, mid_w:],
        x[:, :, mid_h:, :mid_w],
        x[:, :, mid_h:, mid_w:],
    ]
    parts = [region.mean(axis=(2, 3)) for region in regions]
    return np.concatenate(parts, axis=1)


def quadrant_backward(grad, shape):
    n, channels, height, width = shape
    mid_h, mid_w = height // 2, width // 2
    boxes = [
        (slice(0, mid_h), slice(0, mid_w)),
        (slice(0, mid_h), slice(mid_w, None)),
        (slice(mid_h, None), slice(0, mid_w)),
        (slice(mid_h, None), slice(mid_w, None)),
    ]
    out = np.zeros(shape, dtype=np.float32)
    for index, (ys, xs) in enumerate(boxes):
        region = out[:, :, ys, xs]
        area = region.shape[2] * region.shape[3]
        piece = grad[:, index * channels : (index + 1) * channels]
        out[:, :, ys, xs] = piece[:, :, None, None] / area
    return out


def softmax(logits):
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def normalize_uint8(image):
    return image.astype(np.float32) / 127.5 - 1.0


def forward_loops(image, weights):
    """One NCHW image, the same arithmetic as the firmware loops."""
    x = image[None, ...] if image.ndim == 3 else image
    assert x.shape[0] == 1
    w1, b1, w2, b2, w3, b3, wd, bd = weights
    current = x[0]
    layers = ((w1, b1), (w2, b2), (w3, b3))
    for weight, bias in layers:
        out_c, in_c, _, _ = weight.shape
        _, height, width = current.shape
        out_h = (height - 3) // 2 + 1
        out_w = (width - 3) // 2 + 1
        nxt = np.zeros((out_c, out_h, out_w), dtype=np.float32)
        for oc in range(out_c):
            for oy in range(out_h):
                for ox in range(out_w):
                    acc = float(bias[oc])
                    for ic in range(in_c):
                        for ky in range(3):
                            iy = oy * 2 + ky
                            row = current[ic, iy]
                            kernel = weight[oc, ic, ky]
                            acc += float(row[ox * 2] * kernel[0] + row[ox * 2 + 1] * kernel[1] + row[ox * 2 + 2] * kernel[2])
                    nxt[oc, oy, ox] = acc if acc > 0.0 else 0.0
        current = nxt
    channels, height, width = current.shape
    mid_h, mid_w = height // 2, width // 2
    regions = [
        current[:, :mid_h, :mid_w],
        current[:, :mid_h, mid_w:],
        current[:, mid_h:, :mid_w],
        current[:, mid_h:, mid_w:],
    ]
    pooled = np.concatenate([region.reshape(channels, -1).mean(axis=1) for region in regions], axis=0)
    logits = wd @ pooled + bd
    probs = softmax(logits[None, :])[0]
    return probs


class TinyCnn:
    def __init__(self, rng=None):
        self.rng = np.random.default_rng(None if rng is None else rng)
        f1, f2, f3 = FILTERS
        self.w1, self.b1 = self._conv(f1, 1)
        self.w2, self.b2 = self._conv(f2, f1)
        self.w3, self.b3 = self._conv(f3, f2)
        self.wd = self.rng.normal(0, np.sqrt(2.0 / (f3 * 4)), size=(CLASSES, f3 * 4)).astype(np.float32)
        self.bd = np.zeros(CLASSES, dtype=np.float32)
        self.velocity = {name: np.zeros_like(value) for name, value in self.parameters()}

    def _conv(self, out_c, in_c):
        scale = np.sqrt(2.0 / (in_c * 9))
        weight = self.rng.normal(0, scale, size=(out_c, in_c, 3, 3)).astype(np.float32)
        bias = np.zeros(out_c, dtype=np.float32)
        return weight, bias

    def parameters(self):
        return [
            ("w1", self.w1),
            ("b1", self.b1),
            ("w2", self.w2),
            ("b2", self.b2),
            ("w3", self.w3),
            ("b3", self.b3),
            ("wd", self.wd),
            ("bd", self.bd),
        ]

    def pack(self):
        return (self.w1, self.b1, self.w2, self.b2, self.w3, self.b3, self.wd, self.bd)

    def forward(self, images):
        x = images if images.ndim == 4 else images[:, None, :, :]
        y1, pre1 = conv_s2(x, self.w1, self.b1)
        y2, pre2 = conv_s2(y1, self.w2, self.b2)
        y3, pre3 = conv_s2(y2, self.w3, self.b3)
        pooled = quadrant_pool(y3)
        logits = pooled @ self.wd.T + self.bd
        cache = {"x": x, "y1": y1, "pre1": pre1, "y2": y2, "pre2": pre2, "y3": y3, "pre3": pre3, "pooled": pooled}
        return logits, cache

    def loss_and_grad(self, images, labels):
        logits, cache = self.forward(images)
        probs = softmax(logits)
        n = labels.shape[0]
        loss = -np.mean(np.log(probs[np.arange(n), labels] + 1e-8))
        grad_logits = probs
        grad_logits[np.arange(n), labels] -= 1.0
        grad_logits /= n

        grad_wd = grad_logits.T @ cache["pooled"]
        grad_bd = grad_logits.sum(axis=0)
        grad_pooled = grad_logits @ self.wd
        grad_y3 = quadrant_backward(grad_pooled, cache["y3"].shape)
        grad_pre3 = grad_y3 * (cache["pre3"] > 0)
        grad_y2, grad_w3, grad_b3 = conv_s2_backward(cache["y2"], self.w3, grad_pre3)
        grad_pre2 = grad_y2 * (cache["pre2"] > 0)
        grad_y1, grad_w2, grad_b2 = conv_s2_backward(cache["y1"], self.w2, grad_pre2)
        grad_pre1 = grad_y1 * (cache["pre1"] > 0)
        _, grad_w1, grad_b1 = conv_s2_backward(cache["x"], self.w1, grad_pre1)
        grads = {
            "w1": grad_w1,
            "b1": grad_b1,
            "w2": grad_w2,
            "b2": grad_b2,
            "w3": grad_w3,
            "b3": grad_b3,
            "wd": grad_wd,
            "bd": grad_bd,
        }
        return float(loss), grads, probs

    def sgd(self, grads, lr=0.05, momentum=0.9, weight_decay=1e-4):
        for name, value in self.parameters():
            grad = grads[name] + weight_decay * value
            self.velocity[name] = momentum * self.velocity[name] + grad.astype(np.float32)
            value -= lr * self.velocity[name]

    def predict(self, images):
        logits, _ = self.forward(images)
        return softmax(logits).argmax(axis=1), softmax(logits)
