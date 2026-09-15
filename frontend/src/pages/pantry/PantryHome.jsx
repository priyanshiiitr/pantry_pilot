import { Link } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext.jsx";
import Layout from "../../components/Layout.jsx";

/** PantryHome — placeholder dashboard. Incoming deliveries arrive in Step 10. */
export default function PantryHome() {
  const { user } = useAuth();
  return (
    <Layout title="Pantry dashboard">
      <p className="muted">
        Welcome, {user.display_name}. Incoming deliveries you can accept or decline arrive in Step 10.
      </p>
      <p>
        <Link to="/pantry/profile">Edit your profile →</Link>
      </p>
    </Layout>
  );
}
