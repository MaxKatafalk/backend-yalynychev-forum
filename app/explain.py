from .database import engine


def explain():
    query = """
    SELECT id, title, author, status
    FROM topics
    WHERE author = ?
    ORDER BY id
    LIMIT 10 OFFSET 0
    """
    with engine.connect() as connection:
        rows = connection.exec_driver_sql("EXPLAIN QUERY PLAN " + query, ("Иван",))
        for row in rows:
            print(row[3])


if __name__ == "__main__":
    explain()
