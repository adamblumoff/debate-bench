import type { ReactNode } from "react";
import "./redesigns.css";

export default function RedesignsLayout({
  children,
}: {
  children: ReactNode;
}) {
  return <div className="redesign-root">{children}</div>;
}
