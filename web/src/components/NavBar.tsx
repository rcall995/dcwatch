import { NavLink } from "react-router-dom";
import styles from "./NavBar.module.css";

function NavBar() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `${styles.navLink} ${isActive ? styles.navLinkActive : ""}`;

  return (
    <nav className={styles.nav}>
      <NavLink to="/" end className={linkClass}>
        <span className={styles.icon}>&#8962;</span>
        <span className={styles.label}>Home</span>
      </NavLink>
      <NavLink to="/leaderboard" className={linkClass}>
        <span className={styles.icon}>&#9733;</span>
        <span className={styles.label}>Leaderboard</span>
      </NavLink>
      <NavLink to="/search" className={linkClass}>
        <span className={styles.icon}>&#128269;</span>
        <span className={styles.label}>Search</span>
      </NavLink>
      <NavLink to="/about" className={linkClass}>
        <span className={styles.icon}>&#9432;</span>
        <span className={styles.label}>About</span>
      </NavLink>
    </nav>
  );
}

export default NavBar;
