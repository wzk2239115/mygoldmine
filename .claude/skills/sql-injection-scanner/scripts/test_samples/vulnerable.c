#include <stdio.h>
#include <sqlite3.h>

int main() {
    sqlite3 *db;
    char *sql_query = "SELECT * FROM users WHERE id = '" + user_input + "'";

    // Vulnerable: direct SQL execution with user input
    sqlite3_exec(db, sql_query, NULL, NULL, NULL);

    return 0;
}
