import { Container } from "@/components/layout/container";
import { ServiceDetailsView } from "@/components/service/service-details-view";

export default function ServicePage() {
  return (
    <Container className="py-8 sm:py-12">
      <ServiceDetailsView />
    </Container>
  );
}
