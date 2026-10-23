import { Link } from "react-router";
import { useFocusOnMount, usePageTitle } from "../lib/hooks";
import { linkClass } from "../lib/ui";

export function NotFoundPage() {
  usePageTitle("Page not found");
  const headingRef = useFocusOnMount<HTMLHeadingElement>();
  return (
    <div className="py-16 text-center">
      <h1 ref={headingRef} tabIndex={-1} className="font-display text-2xl font-bold text-ink-900">
        Page not found
      </h1>
      <p className="mt-2 text-ink-600">
        <Link to="/quotes" className={linkClass}>
          Go to quotes
        </Link>
      </p>
    </div>
  );
}
