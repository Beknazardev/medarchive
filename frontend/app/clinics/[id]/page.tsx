import { Container } from "@/components/layout/container";
import { ClinicDetailsView } from "@/components/clinic/clinic-details-view";

export default function ClinicPage() {
  return (
    <Container className="py-8 sm:py-12">
      <ClinicDetailsView />
    </Container>
  );
}
