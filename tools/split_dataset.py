"""Split a big dataset ZIP into several smaller ZIPs (whole sessions are never cut), so each fits the free-tier limits.

    python tools/split_dataset.py Dataset.zip --sessions 12
    -> Dataset_part01.zip, Dataset_part02.zip, ...   (same folder structure, originals untouched)
"""
import argparse, collections, os, posixpath, zipfile


def session_key(path: str) -> str:
    p = posixpath.normpath(path.replace("\\", "/"))
    return p.split("/ecg/")[0] if "/ecg/" in p else posixpath.dirname(p)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip"); ap.add_argument("--sessions", type=int, default=12, help="sessions per part (default 12)")
    a = ap.parse_args()
    src = zipfile.ZipFile(a.zip)
    groups: dict[str, list] = collections.OrderedDict()
    for i in src.infolist():
        if i.is_dir() or "__MACOSX" in i.filename or posixpath.basename(i.filename).startswith("."):
            continue
        groups.setdefault(session_key(i.filename), []).append(i)
    keys = sorted(groups)
    base = os.path.splitext(a.zip)[0]
    for n in range(0, len(keys), a.sessions):
        out = f"{base}_part{n // a.sessions + 1:02d}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for k in keys[n:n + a.sessions]:
                for i in groups[k]:
                    z.writestr(i.filename, src.read(i))
        print(f"{out}: {len(keys[n:n + a.sessions])} sessions, {os.path.getsize(out) / 1048576:.1f} MB")


if __name__ == "__main__":
    main()
