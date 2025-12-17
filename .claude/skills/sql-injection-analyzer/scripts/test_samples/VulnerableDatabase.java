import java.sql.*;

public class VulnerableDatabase {

    // Test 1: Statement.executeQuery
    public void queryDatabase(String userId) throws SQLException {
        Connection conn = DriverManager.getConnection("jdbc:mysql://localhost/mydb", "root", "password");
        Statement stmt = conn.createStatement();
        String sql = "SELECT * FROM users WHERE id = " + userId;
        ResultSet rs = stmt.executeQuery(sql);
    }

    // Test 2: Statement.executeUpdate
    public void updateDatabase(String tableName, String value) throws SQLException {
        Connection conn = DriverManager.getConnection("jdbc:mysql://localhost/mydb", "root", "password");
        Statement stmt = conn.createStatement();
        String sql = "UPDATE " + tableName + " SET status = '" + value + "'";
        stmt.executeUpdate(sql);
    }

    // Test 3: Statement.execute
    public void executeDatabase(String command) throws SQLException {
        Connection conn = DriverManager.getConnection("jdbc:mysql://localhost/mydb", "root", "password");
        Statement stmt = conn.createStatement();
        stmt.execute("SELECT * FROM " + command);
    }

    // Test 4: Spring JdbcTemplate.query
    public void springQuery(String name) {
        String sql = "SELECT * FROM users WHERE name = '" + name + "'";
        List<User> users = jdbcTemplate.query(sql, new UserRowMapper());
    }
}
