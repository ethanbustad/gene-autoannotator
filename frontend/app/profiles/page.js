import AppShell from "../../components/AppShell";
import ProfileWorkspace from "../../components/ProfileWorkspace";

export const metadata = {
  title: "Profiles · Gene Autoannotator",
};

export default function ProfilesPage() {
  return (
    <AppShell>
      <ProfileWorkspace />
    </AppShell>
  );
}
