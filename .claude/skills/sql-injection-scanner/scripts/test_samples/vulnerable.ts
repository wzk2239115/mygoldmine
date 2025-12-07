import React, { useState } from 'react';

interface UserData {
  id: number;
  name: string;
}

const App: React.FC = () => {
  const [user, setUser] = useState<UserData | null>(null);

  const fetchUser = async (userId: string): Promise<void> => {
    // Vulnerable: SQL injection in TypeScript
    const query = `SELECT * FROM users WHERE id = ${userId}`;

    const response = await fetch('/api/query', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });

    const data = await response.json();
    setUser(data);
  };

  const handleSearch = (input: string): void => {
    fetchUser(input);
  };

  return (
    <div>
      <input onChange={(e) => handleSearch(e.target.value)} />
    </div>
  );
};

export default App;
