import { AppHeader } from "../components/app/AppHeader";
import { ProfileWorkspace } from "../components/characters/ProfileWorkspace";
export const metadata = { title: "Profile | Alpha Poker" };
export default function ProfilePage() {
  return <><AppHeader currentPath="/profile" /><ProfileWorkspace /></>;
}
