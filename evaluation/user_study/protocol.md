# User study

Minimum 5 participants, as the course requires. This file is the plan. It does not contain results.

## Question

Can a person move, like, and pause a TikTok video with the four poses as reliably as with the keyboard, and how much slower is it?

## Design

Within subjects. Each person does the task with the keyboard and with the gesture controller. Flip a coin, or alternate by participant number, so half start with the keyboard. The keyboard condition is the baseline.

The TikTok window must be focused. Use the same account, the same starting video, and the same laptop. Train the model before the study, and say in the write-up whether any participant also appears in the training set.

## Task

Read `tasks.md` aloud. One trial is: go to the next video, go back, like the current video, pause, play.

## Measures

- Time from "start" to the last correct action, in seconds.
- Wrong keys or wrong videos.
- After both conditions, which one they would use if their hands were busy, and one sentence on why.

## Consent

Read `consent.md` first. A person can stop without giving a reason. Do not record faces unless they agree. The camera on the ESP32 is pointed at their hand. Do not upload those frames anywhere but this private repo.

## Analysis

Put one row per participant per condition in `responses.csv`, then run:

```bash
python evaluation/user_study/analyze.py
```

The script prints means. With five people it will not claim statistical significance. If the CSV is still the template, the script stops.
