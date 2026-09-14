"""Download and verify the four official ACS 1-year Texas PUMS archives."""
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlretrieve

from solve import CHECKSUMS


def download(data_dir, key):
    year, filename = key.split('/')
    url = f'https://www2.census.gov/programs-surveys/acs/data/pums/{year}/1-Year/{filename}'
    path = data_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix('.zip.part')
        urlretrieve(url, temporary)
        assert hashlib.sha256(temporary.read_bytes()).hexdigest() == CHECKSUMS[key], key
        temporary.replace(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == CHECKSUMS[key], key
    return f'Verified {path}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for message in pool.map(lambda key: download(args.data_dir, key), CHECKSUMS):
            print(message, flush=True)


if __name__ == '__main__':
    main()
