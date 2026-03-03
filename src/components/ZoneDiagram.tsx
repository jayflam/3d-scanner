import type { DamageItem, VehicleZone, Severity } from "../lib/api-types";

interface ZoneDiagramProps {
  damages: DamageItem[];
  onZoneClick?: (zone: VehicleZone) => void;
}

/** Top-down vehicle outline SVG with clickable damage zones */
export default function ZoneDiagram({ damages, onZoneClick }: ZoneDiagramProps) {
  // Compute severity per zone (use the worst severity found)
  const zoneSeverity = new Map<VehicleZone, Severity>();
  for (const d of damages) {
    const current = zoneSeverity.get(d.vehicle_zone);
    if (!current || SEVERITY_RANK[d.severity] > SEVERITY_RANK[current]) {
      zoneSeverity.set(d.vehicle_zone, d.severity);
    }
  }

  const handleClick = (zone: VehicleZone) => {
    onZoneClick?.(zone);
    // Scroll to the damage card for this zone
    const el = document.getElementById(`damage-${zone}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring-2", "ring-blue-500");
      setTimeout(() => el.classList.remove("ring-2", "ring-blue-500"), 2000);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <h3 className="text-sm font-medium text-slate-300 mb-3">
        Damage Zone Map
      </h3>

      <svg
        viewBox="0 0 200 400"
        className="w-full max-w-[200px] mx-auto"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Vehicle body outline */}
        <path
          d="M60,50 Q60,20 100,15 Q140,20 140,50 L145,100 L150,150 L150,280 L145,330 Q140,380 100,385 Q60,380 55,330 L50,280 L50,150 L55,100 Z"
          fill="none"
          stroke="#334155"
          strokeWidth="2"
        />

        {/* Windshield */}
        <path
          d="M70,95 Q100,80 130,95 L130,130 Q100,120 70,130 Z"
          fill="none"
          stroke="#334155"
          strokeWidth="1"
          strokeDasharray="4,2"
        />

        {/* Rear window */}
        <path
          d="M70,295 Q100,285 130,295 L130,330 Q100,320 70,330 Z"
          fill="none"
          stroke="#334155"
          strokeWidth="1"
          strokeDasharray="4,2"
        />

        {/* Wheel wells */}
        <ellipse cx="55" cy="120" rx="10" ry="18" fill="none" stroke="#334155" strokeWidth="1.5" />
        <ellipse cx="145" cy="120" rx="10" ry="18" fill="none" stroke="#334155" strokeWidth="1.5" />
        <ellipse cx="55" cy="300" rx="10" ry="18" fill="none" stroke="#334155" strokeWidth="1.5" />
        <ellipse cx="145" cy="300" rx="10" ry="18" fill="none" stroke="#334155" strokeWidth="1.5" />

        {/* Clickable zones */}
        {ZONE_PATHS.map(({ zone, d, labelX, labelY }) => {
          const severity = zoneSeverity.get(zone);
          const fillColor = severity ? SEVERITY_FILL[severity] : "transparent";
          const hasDamage = !!severity;

          return (
            <g key={zone} className="cursor-pointer" onClick={() => handleClick(zone)}>
              <path
                d={d}
                fill={fillColor}
                stroke={hasDamage ? SEVERITY_STROKE[severity!] : "transparent"}
                strokeWidth={hasDamage ? 1.5 : 0}
                className="transition-all hover:opacity-80"
                opacity={hasDamage ? 0.6 : 0.1}
              />
              {/* Zone label */}
              <text
                x={labelX}
                y={labelY}
                textAnchor="middle"
                className="text-[7px] fill-slate-500 select-none pointer-events-none"
              >
                {ZONE_LABELS[zone]}
              </text>
              {/* Damage indicator dot */}
              {hasDamage && (
                <circle
                  cx={labelX}
                  cy={labelY - 12}
                  r="4"
                  fill={SEVERITY_STROKE[severity!]}
                  className="animate-pulse"
                />
              )}
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex justify-center gap-4 mt-3 text-xs text-slate-400">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          Minor
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
          Moderate
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
          Severe
        </div>
      </div>
    </div>
  );
}

// -- Zone geometry and config ------------------------------------------------

const SEVERITY_RANK: Record<Severity, number> = {
  minor: 1,
  moderate: 2,
  severe: 3,
};

const SEVERITY_FILL: Record<Severity, string> = {
  minor: "rgba(16, 185, 129, 0.25)",
  moderate: "rgba(234, 179, 8, 0.25)",
  severe: "rgba(239, 68, 68, 0.25)",
};

const SEVERITY_STROKE: Record<Severity, string> = {
  minor: "#10b981",
  moderate: "#eab308",
  severe: "#ef4444",
};

const ZONE_LABELS: Record<VehicleZone, string> = {
  front_center: "Front",
  front_left: "FL",
  front_right: "FR",
  rear_center: "Rear",
  rear_left: "RL",
  rear_right: "RR",
  side_left: "Left",
  side_right: "Right",
  roof: "Roof",
};

interface ZonePath {
  zone: VehicleZone;
  d: string;
  labelX: number;
  labelY: number;
}

const ZONE_PATHS: ZonePath[] = [
  {
    zone: "front_center",
    d: "M75,30 Q100,20 125,30 L130,65 Q100,55 70,65 Z",
    labelX: 100,
    labelY: 52,
  },
  {
    zone: "front_left",
    d: "M55,60 L70,65 Q65,90 60,100 L50,100 Q48,75 55,60 Z",
    labelX: 60,
    labelY: 85,
  },
  {
    zone: "front_right",
    d: "M145,60 L130,65 Q135,90 140,100 L150,100 Q152,75 145,60 Z",
    labelX: 140,
    labelY: 85,
  },
  {
    zone: "side_left",
    d: "M50,140 L65,140 L65,280 L50,280 Z",
    labelX: 57,
    labelY: 215,
  },
  {
    zone: "side_right",
    d: "M135,140 L150,140 L150,280 L135,280 Z",
    labelX: 143,
    labelY: 215,
  },
  {
    zone: "roof",
    d: "M75,140 L125,140 L125,280 L75,280 Z",
    labelX: 100,
    labelY: 215,
  },
  {
    zone: "rear_left",
    d: "M50,320 L60,320 Q65,330 70,350 L55,360 Q48,345 50,320 Z",
    labelX: 60,
    labelY: 342,
  },
  {
    zone: "rear_right",
    d: "M150,320 L140,320 Q135,330 130,350 L145,360 Q152,345 150,320 Z",
    labelX: 140,
    labelY: 342,
  },
  {
    zone: "rear_center",
    d: "M70,350 Q100,345 130,350 L125,375 Q100,382 75,375 Z",
    labelX: 100,
    labelY: 368,
  },
];
