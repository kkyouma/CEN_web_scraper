# CEN Web Scraper

This tool streamlines the process of downloading data from the [CEN (Coordinador Eléctrico Nacional)](https://www.coordinador.cl/) by using public access links.

## Installation

This project uses [UV](https://docs.astral.sh/uv/) as its package manager. If you don't have UV installed, follow the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

## Usage

> [!NOTE]
> This usage example is provisional. The interface is currently under development.

To run the scraper:

1. Clone this repository.
2. Open the `lets_scrape.py` file.
3. Modify the lines under the `if __name__ == "__main__":` block to set your desired download dates.

Example:

```python
dates_for_batch = [
    (2024, 11),
    (2024, 12),
    (2025, 1),
    (2025, 2),
]

download_cen_files_batch(
    dates_to_download=dates_for_batch,
    download_type_setting="unidad",
    file_format_setting="tsv",
)
```
