import { useState, useEffect } from "react";
import styles from "./ThemeToggle.module.css";

function ThemeToggle() {
  const [isLight, setIsLight] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("dc-watcher-theme");
    if (stored === "light") {
      setIsLight(true);
      document.documentElement.classList.add("light");
    }
  }, []);

  const toggle = () => {
    const next = !isLight;
    setIsLight(next);
    if (next) {
      document.documentElement.classList.add("light");
      localStorage.setItem("dc-watcher-theme", "light");
    } else {
      document.documentElement.classList.remove("light");
      localStorage.setItem("dc-watcher-theme", "dark");
    }
  };

  return (
    <button
      className={styles.button}
      onClick={toggle}
      aria-label={isLight ? "Switch to dark mode" : "Switch to light mode"}
      title={isLight ? "Switch to dark mode" : "Switch to light mode"}
    >
      {isLight ? "\u263E" : "\u2600"}
    </button>
  );
}

export default ThemeToggle;
