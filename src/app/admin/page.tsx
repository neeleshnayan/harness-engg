import { redirect } from "next/navigation";

// Admin entry point — the operator (Rushi) surface. The Strategy Studio cockpit
// and Clark chat are the two admin views; both live in this same app/codebase.
export default function AdminPage() {
  redirect("/clark/studio");
}
