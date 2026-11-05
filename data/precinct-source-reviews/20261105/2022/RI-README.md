[![Build Status](https://github.com/openelections/openelections-data-ri/actions/workflows/data_tests.yml/badge.svg?branch=master)](https://github.com/openelections/openelections-data-ri/actions/workflows/data_tests.yml?query=branch%3Amaster)

# OpenElections Data Rhode Island

This repository contains CSV files with Rhode Island election results. Results from 2018 onward are fetched directly from the [Rhode Island Board of Elections](https://www.ri.gov/election/results/) fixed-width data files using `parser.py`. Older results were converted from earlier source files. Filenames follow the [OpenElections naming conventions](http://docs.openelections.net/archive-standardization/).

## Parser

`parser.py` downloads and parses the RI Board of Elections fixed-width data files (long or short format) and produces OpenElections-formatted CSVs. Dependencies are managed with [uv](https://docs.astral.sh/uv/). To install:

```
uv sync
```

### Usage

```
uv run python parser.py (--year YEAR | --url URL) [--election-type TYPE] [--date YYYYMMDD] [--precinct] [--output PATH]
```

Output is written to a year-based subdirectory (e.g. `2024/`) and named automatically from the date, election type, and geography level.

### Examples

General election, town-level results:
```
uv run python parser.py --year 2024 --date 20241105
```

Statewide primary, precinct-level results:
```
uv run python parser.py --year 2024 --date 20240813 --election-type primary --precinct
```

Presidential preference primary:
```
uv run python parser.py --year 2024 --date 20240402 --election-type presidential-primary
```

Special election:
```
uv run python parser.py --year 2023 --date 20230905 --election-type special
```

Direct URL (long format):
```
uv run python parser.py --url https://www.ri.gov/election/results/2024/general_election/data/rigen2024l.zip --date 20241105
```

### Election types

| `--election-type` | Description |
|---|---|
| `general` (default) | General election |
| `primary` | Statewide primary |
| `presidential-primary` | Presidential preference primary |
| `special` | Special election |

### Output columns

Town-level files: `county, office, district, party, candidate, votes, election_day, mail, early_voting`

Precinct-level files (with `--precinct`): `county, precinct, office, district, party, candidate, votes, election_day, mail, early_voting`

## Results Inventory

### 2024

| File | Type |
|---|---|
| [2024/20240402__ri__primary__president__town.csv](2024/20240402__ri__primary__president__town.csv) | Presidential primary, town |
| [2024/20240402__ri__primary__president__precinct.csv](2024/20240402__ri__primary__president__precinct.csv) | Presidential primary, precinct |
| [2024/20240813__ri__primary__town.csv](2024/20240813__ri__primary__town.csv) | Primary, town |
| [2024/20240813__ri__primary__precinct.csv](2024/20240813__ri__primary__precinct.csv) | Primary, precinct |
| [2024/20241105__ri__general__town.csv](2024/20241105__ri__general__town.csv) | General, town |
| [2024/20241105__ri__general__precinct.csv](2024/20241105__ri__general__precinct.csv) | General, precinct |

### 2023

| File | Type |
|---|---|
| [2023/20230905__ri__special__town.csv](2023/20230905__ri__special__town.csv) | Special election, town |
| [2023/20231107__ri__general__town.csv](2023/20231107__ri__general__town.csv) | General, town |
| [2023/20231107__ri__general__precinct.csv](2023/20231107__ri__general__precinct.csv) | General, precinct |

### 2022

| File | Type |
|---|---|
| [2022/20220913__ri__primary__town.csv](2022/20220913__ri__primary__town.csv) | Primary, town |
| [2022/20220913__ri__primary__precinct.csv](2022/20220913__ri__primary__precinct.csv) | Primary, precinct |
| [2022/20221108__ri__general__town.csv](2022/20221108__ri__general__town.csv) | General, town |
| [2022/20221108__ri__general__precinct.csv](2022/20221108__ri__general__precinct.csv) | General, precinct |

### 2021

| File | Type |
|---|---|
| [2021/20210302__ri__special__town.csv](2021/20210302__ri__special__town.csv) | Special election, town |
| [2021/20210302__ri__special__precinct.csv](2021/20210302__ri__special__precinct.csv) | Special election, precinct |

### 2020

| File | Type |
|---|---|
| [2020/20200609__ri__primary__president__town.csv](2020/20200609__ri__primary__president__town.csv) | Presidential primary, town |
| [2020/20200609__ri__primary__president__precinct.csv](2020/20200609__ri__primary__president__precinct.csv) | Presidential primary, precinct |
| [2020/20200908__ri__primary__town.csv](2020/20200908__ri__primary__town.csv) | Primary, town |
| [2020/20200908__ri__primary__precinct.csv](2020/20200908__ri__primary__precinct.csv) | Primary, precinct |
| [2020/20201103__ri__general__town.csv](2020/20201103__ri__general__town.csv) | General, town |
| [2020/20201103__ri__general__precinct.csv](2020/20201103__ri__general__precinct.csv) | General, precinct |

### 2018

| File | Type |
|---|---|
| [2018/20180912__ri__primary__town.csv](2018/20180912__ri__primary__town.csv) | Primary, town |
| [2018/20180912__ri__primary__precinct.csv](2018/20180912__ri__primary__precinct.csv) | Primary, precinct |
| [2018/20181106__ri__general__town.csv](2018/20181106__ri__general__town.csv) | General, town |
| [2018/20181106__ri__general__precinct.csv](2018/20181106__ri__general__precinct.csv) | General, precinct |

### 2016

| File | Type |
|---|---|
| [2016/20160426__ri__primary__president__precinct.csv](2016/20160426__ri__primary__president__precinct.csv) | Presidential primary, precinct |
| [2016/20161108__ri__general__town.csv](2016/20161108__ri__general__town.csv) | General, town |
| [2016/20161108__ri__general__precinct.csv](2016/20161108__ri__general__precinct.csv) | General, precinct |

### 2014

| File | Type |
|---|---|
| [2014/20141104__ri__general__town.csv](2014/20141104__ri__general__town.csv) | General, town |
| [2014/20141104__ri__general__precinct.csv](2014/20141104__ri__general__precinct.csv) | General, precinct |

### 2012

| File | Type |
|---|---|
| [2012/20121106__ri__general__town.csv](2012/20121106__ri__general__town.csv) | General, town |

### 2010

| File | Type |
|---|---|
| [2010/20101102__ri__general__town.csv](2010/20101102__ri__general__town.csv) | General, town |

### 2008

| File | Type |
|---|---|
| [2008/20081104__ri__general__town.csv](2008/20081104__ri__general__town.csv) | General, town |

## Contributing

To contribute, email [openelections@gmail.com](mailto:openelections@gmail.com) or leave a comment on one of the [issues](https://github.com/openelections/openelections-data-ri/issues) in this repository.
