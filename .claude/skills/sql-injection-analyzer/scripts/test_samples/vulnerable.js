// Test 1: MySQL direct query
const mysql = require('mysql');
const connection = mysql.createConnection({
  host: 'localhost',
  user: 'root',
  password: 'password',
  database: 'mydb'
});

const userId = req.query.id;
const sql = `SELECT * FROM users WHERE id = ${userId}`;
connection.query(sql, (error, results) => {
  if (error) throw error;
  console.log(results);
});

// Test 2: Sequelize raw query
const { Sequelize } = require('sequelize');
const sequelize = new Sequelize('database', 'username', 'password');
const userId = req.body.userId;
const result = await sequelize.query(`SELECT * FROM users WHERE id = ${userId}`);

// Test 3: Knex raw
const knex = require('knex');
const db = knex({
  client: 'mysql',
  connection: { host: 'localhost', user: 'root' }
});

const column = req.query.col;
const results = db.raw(`SELECT * FROM users WHERE ${column} = ?`, [value]);

// Test 4: Pool.execute
const { Pool } = require('pg');
const pool = new Pool();
const userInput = req.query.search;
const query = `SELECT * FROM products WHERE name LIKE '%${userInput}%'`;
pool.execute(query, (err, res) => {});
