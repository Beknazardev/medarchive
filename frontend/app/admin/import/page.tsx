import { Container } from "@/components/layout/container";
import { AdminImportForm } from "@/components/admin/admin-import-form";

export default function AdminImportPage() {
  return (
    <Container className="py-8 sm:py-12">
      <AdminImportForm />
    </Container>
  );
}
