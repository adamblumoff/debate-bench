import { Outfit, Roboto_Mono } from "next/font/google";
import { RedesignSwitcher } from "@/app/redesigns/_components/RedesignSwitcher";
import styles from "./glass-operations.module.css";

const display = Outfit({ subsets: ["latin"], weight: ["500", "600", "700", "800"] });
const mono = Roboto_Mono({ subsets: ["latin"], weight: ["400", "500", "700"] });

export default function GlassOperationsPage() {
  return (
    <main className={`${styles.page} ${display.className} ${mono.className}`}>
      <RedesignSwitcher active="glass-operations" />

      <div className={styles.shell}>
        <header className={styles.hero}>
          <p className={styles.kicker}>DebateBench glass prototype</p>
          <h1>Glass Operations</h1>
          <div className={styles.heroPills}>
            <span>run: sample5</span>
            <span>38 models</span>
            <span>6,240 debates</span>
            <span>live pricing</span>
          </div>
        </header>

        <section className={styles.kpiGrid}>
          <article><p>Top model</p><strong>gpt-4.2</strong><span>+42 Elo</span></article>
          <article><p>Win-rate lead</p><strong>62.7%</strong><span>weighted</span></article>
          <article><p>Judge span</p><strong>8.4%</strong><span>variance</span></article>
          <article><p>Side bias</p><strong>1.8%</strong><span>pro-con gap</span></article>
        </section>

        <section className={styles.layout}>
          <article className={styles.panelLarge}>
            <header><h2>Price vs performance cloud</h2><span>Elo mode</span></header>
            <div className={styles.scatter} />
          </article>

          <article className={styles.panel}>
            <header><h2>Run controls mock</h2><span>non-functional</span></header>
            <div className={styles.controlList}>
              <button>Refresh runs</button>
              <button>Refresh data</button>
              <button>Download debates</button>
              <button>Open builder</button>
            </div>
          </article>

          <article className={styles.panel}>
            <header><h2>Topic/category heat grid</h2><span>matrix</span></header>
            <div className={styles.heat} />
          </article>

          <article className={styles.panel}>
            <header><h2>Judge side bias strips</h2><span>cv mean</span></header>
            <div className={styles.bars}>
              <span style={{ width: "82%" }} />
              <span style={{ width: "74%" }} />
              <span style={{ width: "61%" }} />
              <span style={{ width: "69%" }} />
            </div>
          </article>

          <article className={`${styles.panel} ${styles.panelWide}`}>
            <header><h2>Pricing ladder</h2><span>USD per 1M tokens</span></header>
            <div className={styles.table}>
              <div><span>gpt-4.2</span><span>$1.10</span><span>$4.20</span></div>
              <div><span>claude-sonnet</span><span>$1.50</span><span>$7.00</span></div>
              <div><span>gemini-2.5</span><span>$0.80</span><span>$3.30</span></div>
              <div><span>qwen-max</span><span>$0.70</span><span>$2.90</span></div>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}
