import { Link } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext.jsx";
import Layout from "../../components/Layout.jsx";

/** DriverHome — placeholder dashboard. Dispatch requests arrive in Step 10. */
export default function DriverHome() {
  const { user } = useAuth();
  return (
    <Layout title="Driver dashboard">
      <p className="muted">Welcome, {user.display_name}. Pickup requests you can accept or decline arrive in Step 10.</p>
      <p>
        <Link to="/driver/profile">Edit your profile →</Link>
      </p>
    </Layout>
  );
}
