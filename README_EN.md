<div align="center">

<img src="docs/logo.png" width="120" alt="Beamplots">

# Beamplots

**English** · [中文](README.md)

**Beamplots of publication output, citation impact, and career time for one researcher**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt](https://img.shields.io/badge/PyQt-5-41CD52?logo=qt&logoColor=white)](https://www.qt.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-oscimetrix--garden%2FBeamplots-181717?logo=github&logoColor=white)](https://github.com/oscimetrix-garden/Beamplots)

[Introduction](#introduction) ·
[Interface](#interface) ·
[Features](#features) ·
[Quick start](#quick-start) ·
[Authors](#authors) ·
[License](#license)

</div>

## Introduction

Beamplots is a desktop app (code version 0.1.0). It reads Web of Science exports (`.txt` / `.ciw` / `.wos`), takes publication year (`PY`) and times cited (`TC`), draws a beamplot, and computes a set of standard bibliometric indicators.

The h-index compresses a career into one number. A beamplot shows yearly output, the citation range and median, and how that picture changes over time. The method follows Haunschild, Bornmann, and Adams. This repository implements the workflow in Python, matching `BibPlots::beamplot()`, including optional age weighting.

A Robin Haunschild WoS sample is bundled. Click Demo to try it. After you add an LLM key in Settings, you can ask questions about the loaded records and chart selections.

## Interface

<div align="center">
<img src="docs/interface.png" alt="Beamplots main window" width="920">
</div>

## Features

- Upload or drop WoS files/folders; bundled Demo data
- Interactive (Plotly) and Static (Matplotlib) plot modes
- Optional age weighting: `TC / min(current year − PY + 1, 11)`
- Sidebar metrics: total citations, average citations, h / g / i10 / hg / π / w / m
- Click or box-select points on the interactive chart; export HTML / PNG / PDF / SVG
- Publications page to inspect and edit records; History to keep past plots
- Chinese/English UI and light/dark themes
- Optional LLM Q&A on the current dataset and chart selection

## Quick start

Environment: Windows 10/11, Python 3.10 or later.

```bash
pip install -r requirements.txt
python main.py
```

See `requirements.txt` for dependencies. Put API keys in local `src/assets/api_keys.json` (gitignored; do not commit).

## Authors

- Jie Li, National Science Library, Chinese Academy of Sciences, China (lijie2022@mail.las.ac.cn)
- Xian Li, National Science Library, Chinese Academy of Sciences, China (lixian@mail.las.ac.cn)
- Robin Haunschild, Max Planck Institute for Solid State Research, Germany (R.Haunschild@fkf.mpg.de)

Main references:

- Haunschild, R., Bornmann, L., & Adams, J. (2019). R package for producing beamplots as a preferred alternative to the h index when assessing single researchers (based on downloads from Web of Science). *Scientometrics*, 120, 925–927.
- Bornmann, L., & Haunschild, R. (2018). Plots for visualizing paper impact and journal impact of single researchers in a single graph. *Scientometrics*, 115(1), 385–394.

## License

This repository is licensed under the [Apache License 2.0](LICENSE).
