export function Header() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-4xl flex-col gap-1 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-lg font-semibold">gptTOpdf</span>
        <span className="text-sm text-muted-foreground">
          Turn conversations into study notes
        </span>
      </div>
    </header>
  );
}
