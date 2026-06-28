import { Suspense } from "react";

import { ComparePageContent } from "@/components/compare/compare-page-content";
import { Container } from "@/components/layout/container";
import { LoadingState } from "@/components/states/loading-state";

export default function ComparePage() {
  return (
    <Container className="py-8 sm:py-12">
      <Suspense fallback={<LoadingState />}>
        <ComparePageContent />
      </Suspense>
    </Container>
  );
}
