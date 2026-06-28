import { Suspense } from "react";

import { Container } from "@/components/layout/container";
import { SearchPageContent } from "@/components/search/search-page-content";
import { LoadingState } from "@/components/states/loading-state";

export default function SearchPage() {
  return (
    <Container className="py-8 sm:py-12">
      <Suspense fallback={<LoadingState />}>
        <SearchPageContent />
      </Suspense>
    </Container>
  );
}
