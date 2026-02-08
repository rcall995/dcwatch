import styles from "./About.module.css";

function About() {
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>About DC Watcher</h1>
      <p className={styles.subtitle}>
        Tracking Congressional stock trades and financial disclosures.
      </p>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>What is DC Watcher?</h2>
        <p className={styles.text}>
          DC Watcher is an open-source tool that tracks stock trades made by
          members of the United States Congress. Every trade reported under the
          STOCK Act is collected, processed, and presented here so the public
          can easily see what their representatives are buying and selling.
        </p>
        <p className={styles.text}>
          The app provides a searchable, filterable view of all disclosed
          transactions, a leaderboard ranking politicians by estimated returns,
          and detailed per-politician trade histories.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Data Sources</h2>
        <p className={styles.text}>
          All data comes from publicly available STOCK Act financial disclosure
          filings. These filings are required by law under the{" "}
          <a
            href="https://en.wikipedia.org/wiki/STOCK_Act"
            target="_blank"
            rel="noopener noreferrer"
            className={styles.link}
          >
            Stop Trading on Congressional Knowledge Act of 2012
          </a>
          . Members of Congress must disclose securities transactions within 45
          days of the trade.
        </p>
        <ul className={styles.list}>
          <li className={styles.listItem}>
            House of Representatives Financial Disclosure Reports
          </li>
          <li className={styles.listItem}>
            Senate Financial Disclosure Reports
          </li>
          <li className={styles.listItem}>
            Market price data for return estimation
          </li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>How Data is Updated</h2>
        <p className={styles.text}>
          The data pipeline runs daily via GitHub Actions. It fetches the latest
          disclosure filings, normalizes them into a consistent format, computes
          estimated returns using market price data, and deploys the updated
          dataset to this site. The entire process is automated and transparent.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Source Code</h2>
        <p className={styles.text}>
          DC Watcher is fully open source. You can review the code, suggest
          improvements, or run your own instance.
        </p>
        <ul className={styles.list}>
          <li className={styles.listItem}>
            <a
              href="https://github.com/dc-watcher"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.link}
            >
              GitHub Repository
            </a>
          </li>
        </ul>
      </div>

      <div className={styles.disclaimer}>
        <div className={styles.disclaimerTitle}>Disclaimer</div>
        <p className={styles.disclaimerText}>
          DC Watcher is provided for informational and educational purposes
          only. Nothing on this site constitutes financial advice, investment
          recommendations, or an endorsement of any trading strategy. The
          estimated return figures are approximate calculations based on
          publicly available data and may not reflect actual gains or losses.
          Always do your own research and consult a qualified financial advisor
          before making investment decisions.
        </p>
      </div>
    </div>
  );
}

export default About;
