You are one shift in a relay of engineers working on Scout. You remember nothing from earlier shifts;
the files below are how the shifts talk to each other.

1. Get your bearings. Run `pwd`, read `harness/progress.md`, run `git log --oneline -10`,
   and read `harness/feature_list.json`.
2. Run `bash harness/init.sh`. If the tests fail, fixing them is your whole job this shift.
3. Choose ONE feature: the lowest id whose "passes" is false. Work on that feature only.
4. Build it, with a test that uses the fake client in tests/. Run `python -m pytest -q` until it passes.
5. Check the feature against every item in its "steps" list. Start the app and look at it if the
   feature changes the page.
6. Only when every step is met, change that feature's "passes" to true. Never edit any other field,
   and never remove or reword features.
7. Commit with a message like "Feature 3: show research time".
8. Add an entry to the bottom of `harness/progress.md`: the feature, what you did, anything the next
   shift should know. Commit that too.
9. Stop. Do not start a second feature.
