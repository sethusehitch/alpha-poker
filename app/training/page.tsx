import { AppHeader } from "../components/app/AppHeader";
import { DojoWorkspace } from "../components/training/DojoWorkspace";
export const metadata = { title: "Training Dojo | Alpha Poker" };
export default function TrainingPage() { return <><AppHeader currentPath="/training" /><DojoWorkspace /></>; }
