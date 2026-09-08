import type { ReactNode } from "react";
import Home from "../page";

/** Keep auth journeys in the site's context without focusable background links. */
export function AuthPageBackdrop({ children }: { children: ReactNode }) {
  return <>
    <div aria-hidden="true" inert className="fixed inset-0 overflow-hidden">
      <Home />
    </div>
    {children}
  </>;
}
