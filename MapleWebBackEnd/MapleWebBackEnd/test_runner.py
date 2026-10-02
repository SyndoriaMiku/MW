"""
Test runner that fails a test when a query would break on PostgreSQL.

Tests run on SQLite, which ignores select_for_update(), while production runs
PostgreSQL, which refuses FOR UPDATE on the nullable side of an outer join
(a nullable foreign key or a reverse one-to-one in select_related). Such a
query passes every SQLite test and fails with a 500 in production, so while
tests run, every compiled locking query is checked: it must either have no
outer join or name its lock targets with select_for_update(of=...).
"""
from django.db.models.sql.compiler import SQLCompiler
from django.db.models.sql.constants import LOUTER
from django.test.runner import DiscoverRunner


class PostgresLockError(AssertionError):
    pass


def _check_lock(compiler):
    query = compiler.query
    if not query.select_for_update or query.select_for_update_of:
        return
    outer = sorted(
        alias.table_name
        for alias in query.alias_map.values()
        if getattr(alias, 'join_type', None) == LOUTER
    )
    if outer:
        raise PostgresLockError(
            f"select_for_update() on {query.model.__name__} outer-joins {', '.join(outer)}; "
            "PostgreSQL refuses FOR UPDATE on the nullable side of an outer join. "
            "Pass of=('self', ...) to lock only the rows that need it."
        )


class PostgresSafeTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._original_as_sql = SQLCompiler.as_sql
        original = self._original_as_sql

        def as_sql(compiler, *args, **kwargs):
            # select_related joins only exist once the query is compiled.
            result = original(compiler, *args, **kwargs)
            _check_lock(compiler)
            return result

        SQLCompiler.as_sql = as_sql

    def teardown_test_environment(self, **kwargs):
        SQLCompiler.as_sql = self._original_as_sql
        super().teardown_test_environment(**kwargs)
