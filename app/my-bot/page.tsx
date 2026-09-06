import type { Metadata } from "next";
import { AppHeader } from "../components/app/AppHeader";
import { MyBotWorkspace } from "../components/mybot/MyBotWorkspace";

export const metadata: Metadata = {
  title: "My Bot — Alpha Poker",
  description: "Your bot, its league standing, and its logs.",
};

export default function MyBotPage() {
  return (
    <>
      <AppHeader currentPath="/my-bot" />
      <MyBotWorkspace />
    </>
  );
}
