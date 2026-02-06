import { Archivo_Black, Space_Mono, Work_Sans } from "next/font/google";
import { RedesignSwitcher } from "@/app/redesigns/_components/RedesignSwitcher";
import styles from "./brutalist-lab.module.css";

const display = Archivo_Black({ subsets: ["latin"], weight: ["400"] });
const body = Work_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });
const mono = Space_Mono({ subsets: ["latin"], weight: ["400", "700"] });

export default function BrutalistLabPage() {
  return (
    <main className={`${styles.page} ${display.className} ${body.className} ${mono.className}`}>
      <RedesignSwitcher active="brutalist-lab" />

      <div className={styles.shell}>
        <header className={styles.hero}>
          <p>NO SOFT UI</p>
          <h1>BRUTALIST LAB</h1>
          <span>Wireframe only · static components · high-contrast hierarchy</span>
        </header>

        <section className={styles.kpiRow}>
          <article><p>TOP ELO</p><strong>GPT-4.2</strong><span>+42</span></article>
          <article><p>JUDGE AGREEMENT</p><strong>82.4%</strong><span>stable</span></article>
          <article><p>SIDE BIAS</p><strong>1.9%</strong><span>contained</span></article>
          <article><p>RUN SIZE</p><strong>6,240</strong><span>debates</span></article>
        </section>

        <section className={styles.matrix}>
          <article className={styles.block}>
            <header><h2>FILTER WALL</h2><span>category + model tags</span></header>
            <div className={styles.tagCloud}>
              <span>POLICY</span><span>SCIENCE</span><span>ECON</span><span>LAW</span>
              <span>GPT-4.2</span><span>CLAUDE</span><span>GEMINI</span><span>QWEN</span>
            </div>
          </article>

          <article className={styles.block}>
            <header><h2>PRICE / ELO</h2><span>scatter board</span></header>
            <div className={styles.scatter} />
          </article>

          <article className={styles.block}>
            <header><h2>HEAD-TO-HEAD</h2><span>win grid</span></header>
            <div className={styles.heat} />
          </article>

          <article className={styles.block}>
            <header><h2>JUDGE BIAS STRIPS</h2><span>cv-adjusted</span></header>
            <div className={styles.barStack}>
              <span style={{ width: "84%" }} />
              <span style={{ width: "71%" }} />
              <span style={{ width: "66%" }} />
              <span style={{ width: "79%" }} />
            </div>
          </article>

          <article className={`${styles.block} ${styles.full}`}>
            <header><h2>COST TABLE</h2><span>input / output per 1M</span></header>
            <div className={styles.table}>
              <div><span>GPT-4.2</span><span>$1.10</span><span>$4.20</span></div>
              <div><span>CLAUDE-SONNET</span><span>$1.50</span><span>$7.00</span></div>
              <div><span>GEMINI-2.5</span><span>$0.80</span><span>$3.30</span></div>
              <div><span>QWEN-MAX</span><span>$0.70</span><span>$2.90</span></div>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}
