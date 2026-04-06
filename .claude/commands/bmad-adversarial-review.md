Load and execute the BMad adversarial review skills. This combines both general adversarial review and edge case hunting:

- Adversarial review: `_bmad/core/bmad-review-adversarial-general/SKILL.md`
- Edge case hunter: `_bmad/core/bmad-review-edge-case-hunter/SKILL.md`

First run bmad-init to load configuration:
```
python _bmad/core/bmad-init/scripts/bmad_init.py load --project-root .
```

Then follow all instructions in both skill files. Start with the general adversarial review, then proceed to edge case hunting.
