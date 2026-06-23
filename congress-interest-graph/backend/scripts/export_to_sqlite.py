import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['POSTGRES_HOST'] = 'localhost'
os.environ['POSTGRES_DB'] = 'congress_graph'
os.environ['POSTGRES_USER'] = 'congress_user'
os.environ['POSTGRES_PASSWORD'] = 'congress_password'

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text, MetaData, Table

EXCLUDE_TABLES = {
    'api_request_logs', 'mock_seed_manifest', 'etl_sources',
}
EXCLUDE_PREFIX = ('sandbox_',)

SQLITE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'congress.db')
os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
if os.path.exists(SQLITE_PATH):
    os.remove(SQLITE_PATH)

pg_engine = create_engine(
    'postgresql+psycopg2://congress_user:congress_password@localhost:5432/congress_graph'
)
sqlite_engine = create_engine(
    f'sqlite:///{SQLITE_PATH}', connect_args={'check_same_thread': False}
)

with sqlite_engine.connect() as conn:
    conn.execute(text('PRAGMA journal_mode=WAL'))
    conn.execute(text('PRAGMA foreign_keys=OFF'))
    conn.commit()

pg_meta = MetaData()
pg_meta.reflect(bind=pg_engine)

sqlite_meta = MetaData()

for table_name in sorted(pg_meta.tables.keys()):
    if table_name in EXCLUDE_TABLES or table_name.startswith(EXCLUDE_PREFIX):
        print(f'SKIP: {table_name}')
        continue

    pg_table = pg_meta.tables[table_name]
    print(f'EXPORT: {table_name} ...', end=' ', flush=True)

    cols = []
    col_type_map = {}
    for col in pg_table.columns:
        type_str = str(col.type).lower()
        if 'json' in type_str or 'jsonb' in type_str:
            col_type = sa.JSON
        elif 'double' in type_str or 'float' in type_str or 'real' in type_str or 'numeric' in type_str:
            col_type = sa.Float
        elif 'integer' in type_str or 'bigint' in type_str or 'smallint' in type_str:
            col_type = sa.Integer
        elif 'boolean' in type_str:
            col_type = sa.Integer
        elif 'timestamp' in type_str or 'datetime' in type_str:
            col_type = sa.DateTime
        elif 'date' in type_str:
            col_type = sa.Date
        else:
            col_type = sa.Text

        col_type_map[col.name] = col_type
        new_col = sa.Column(col.name, col_type, primary_key=col.primary_key)
        cols.append(new_col)

    sqlite_table = Table(table_name, sqlite_meta, *cols, extend_existing=True)
    sqlite_table.create(sqlite_engine, checkfirst=True)

    with pg_engine.connect() as conn:
        rows = conn.execute(pg_table.select()).fetchall()
        if rows:
            batch = []
            for r in rows:
                row_dict = {}
                for col_name in r._mapping.keys():
                    val = r._mapping[col_name]
                    if val is not None:
                        col_type = col_type_map[col_name]
                        if col_type in (sa.DateTime, sa.Date):
                            pass
                        elif isinstance(val, datetime):
                            val = val.isoformat()
                        elif isinstance(val, date):
                            val = val.isoformat()
                        elif isinstance(val, bool):
                            val = 1 if val else 0
                    row_dict[col_name] = val
                batch.append(row_dict)

                if len(batch) >= 500:
                    with sqlite_engine.connect() as sql_conn:
                        with sql_conn.begin():
                            sql_conn.execute(sqlite_table.insert(), batch)
                    batch = []

            if batch:
                with sqlite_engine.connect() as sql_conn:
                    with sql_conn.begin():
                        sql_conn.execute(sqlite_table.insert(), batch)

    with sqlite_engine.connect() as conn:
        count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
    print(f'{count} rows')

sqlite_engine.dispose()

print(f'\nDONE: {SQLITE_PATH}')
print(f'Size: {os.path.getsize(SQLITE_PATH) / 1024 / 1024:.1f} MB')
