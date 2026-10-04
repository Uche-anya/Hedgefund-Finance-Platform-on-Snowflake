"""Load the project's YAML files and report syntax errors."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def yaml_files():
    files = list((ROOT / 'dbt').rglob('*.yml'))
    files.extend((ROOT / '.github').rglob('*.yml'))
    return sorted(path for path in files if 'target' not in path.parts)


def main():
    files = yaml_files()
    for path in files:
        with path.open(encoding='utf-8') as handle:
            yaml.safe_load(handle)
    print(f'Checked {len(files)} YAML files.')


if __name__ == '__main__':
    main()
