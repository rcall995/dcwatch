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
      <NavLink to="/signals" className={linkClass}>
        <span className={styles.icon}>&#9889;</span>
        <span className={styles.label}>Signals</span>
      </NavLink>
      <NavLink to="/portfolio" className={linkClass}>
        <span className={styles.icon}>&#128188;</span>
        <span className={styles.label}>Portfolio</span>
      </NavLink>
      <NavLink to="/search" className={linkClass}>
        <span className={styles.icon}>&#128269;</span>
        <span className={styles.label}>Search</span>
      </NavLink>
    </nav>
  );
}

export default NavBar;
