import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import AuthGate from "./auth/AuthGate";
import { UserProvider } from "./context/UserContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthGate>
        <UserProvider>
          <App />
        </UserProvider>
      </AuthGate>
    </BrowserRouter>
  </React.StrictMode>
);
