const languages = [
  { value: "en", label: "English" },
  { value: "ar", label: "Arabic" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "es", label: "Spanish" },
  { value: "ja", label: "Japanese" }
];

interface LanguageSelectorProps {
  source: string;
  target: string;
  onSourceChange: (value: string) => void;
  onTargetChange: (value: string) => void;
}

export function LanguageSelector({ source, target, onSourceChange, onTargetChange }: LanguageSelectorProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="space-y-2">
        <span className="text-sm font-medium text-slate-300">Source Language</span>
        <select
          value={source}
          onChange={(event) => onSourceChange(event.target.value)}
          className="h-12 w-full rounded-md border border-line bg-white/[0.07] px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-electric/30"
        >
          {languages.map((language) => (
            <option key={language.value} value={language.value} className="bg-ink">
              {language.label}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-2">
        <span className="text-sm font-medium text-slate-300">Target Language</span>
        <select
          value={target}
          onChange={(event) => onTargetChange(event.target.value)}
          className="h-12 w-full rounded-md border border-line bg-white/[0.07] px-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-electric/30"
        >
          {languages.map((language) => (
            <option key={language.value} value={language.value} className="bg-ink">
              {language.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
