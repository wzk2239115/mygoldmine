use sqlx::SqlitePool;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let pool = SqlitePool::connect("sqlite://database.db").await?;

    // Vulnerable: raw SQL with user input
    let user_id = get_user_input();
    let query = format!("SELECT * FROM users WHERE id = {}", user_id);

    // Vulnerable SQL execution
    let rows = sqlx::query(&query)
        .fetch_all(&pool)
        .await?;

    for row in rows {
        println!("User: {:?}", row);
    }

    Ok(())
}

fn get_user_input() -> String {
    "1' OR '1'='1".to_string()
}
