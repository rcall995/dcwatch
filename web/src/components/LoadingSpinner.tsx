import styles from "./LoadingSpinner.module.css";

interface LoadingSpinnerProps {
  message?: string;
}

function LoadingSpinner({ message }: LoadingSpinnerProps) {
  return (
    <div className={styles.container}>
      <div className={styles.spinner} />
      {message && <p className={styles.message}>{message}</p>}
    </div>
  );
}

export default LoadingSpinner;
