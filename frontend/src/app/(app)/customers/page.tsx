import type { Metadata } from "next";
import { Suspense } from "react";

import { CustomersView } from "@/components/customers/customers-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Customers" };

export default function CustomersPage() {
  // CustomersView reads ?id=<customer id> from the URL, so it sits inside Suspense.
  return (
    <Suspense fallback={<CustomersFallback />}>
      <CustomersView />
    </Suspense>
  );
}

function CustomersFallback() {
  return (
    <div className="flex h-full flex-col">
      <div className="h-14 shrink-0 border-b" />
      <div className="space-y-4 p-3 md:w-80 lg:w-[24rem]">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    </div>
  );
}
