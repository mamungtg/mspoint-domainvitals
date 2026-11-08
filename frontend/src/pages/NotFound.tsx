import { Link } from "react-router-dom";
import { linkCls } from "../components/ui";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-md px-4 py-24 text-center">
      <h1 className="text-[26px] font-semibold">This page does not exist</h1>
      <p className="mt-2 text-muted">Check the address, or go back to the start.</p>
      <Link to="/" className={`${linkCls} mt-4 inline-block`}>Go to DomainVitals</Link>
    </main>
  );
}
