Load and execute the BMad research skills located under `_bmad/bmm/1-analysis/research/`.

Available research types:
- Domain research: `_bmad/bmm/1-analysis/research/bmad-domain-research/SKILL.md`
- Market research: `_bmad/bmm/1-analysis/research/bmad-market-research/SKILL.md`
- Technical research: `_bmad/bmm/1-analysis/research/bmad-technical-research/SKILL.md`

First run bmad-init to load configuration:
```
python _bmad/core/bmad-init/scripts/bmad_init.py load --project-root . --module bmm
```

Ask the user which type of research they want to conduct (domain, market, or technical), then follow all instructions in the corresponding skill file.
