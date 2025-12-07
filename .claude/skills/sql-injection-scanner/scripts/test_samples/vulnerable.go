package main

import (
	"database/sql"
	"fmt"

	_ "github.com/go-sql-driver/mysql"
)

func main() {
	db, _ := sql.Open("mysql", "user:password@/dbname")

	// Vulnerable: direct SQL query with user input
	query := "SELECT * FROM users WHERE id = " + userId

	rows, _ := db.Query(query)
	defer rows.Close()

	// Process results
	for rows.Next() {
		var id int
		var name string
		rows.Scan(&id, &name)
		fmt.Println(id, name)
	}
}
