"""Copy a SQLite save consistently without overwriting either existing file."""
import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def copy_save(source: Path, destination: Path):
    source=source.resolve(strict=True)
    destination=destination.resolve()
    if source==destination: raise ValueError("Source and destination must differ")
    with destination.open("xb"):
        pass
    with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True)) as original:
        original.execute("BEGIN")
        tables=[r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        with closing(sqlite3.connect(destination)) as target:
            original.backup(target)
            assert target.execute("PRAGMA integrity_check").fetchone()==("ok",)
            for table in tables:
                quoted='"'+table.replace('"','""')+'"'
                assert original.execute("SELECT * FROM "+quoted).fetchall()==target.execute("SELECT * FROM "+quoted).fetchall(), table
        original.rollback()
    return {"source":str(source),"copy":str(destination),"tables_preserved":len(tables),"integrity":"ok"}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    print(json.dumps(copy_save(args.source,args.destination),ensure_ascii=False,indent=2))
