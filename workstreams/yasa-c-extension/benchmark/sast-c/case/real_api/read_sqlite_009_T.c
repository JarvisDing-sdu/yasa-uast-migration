/*
 * evaluation information start
 * real case = true
 * evaluation item = 真实 API
 * scene introduction = read → sqlite3_exec SQL 注入
 * bind_url = real_api/read_sqlite_009_T
 * evaluation information end
 */
#include <unistd.h>
#include <sqlite3.h>
void read_sqlite_009_T(sqlite3 *db) {
    char q[256];
    read(0, q, sizeof(q));
    sqlite3_exec(db, q, 0, 0, 0);
}
