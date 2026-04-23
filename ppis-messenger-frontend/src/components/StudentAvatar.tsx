import { getStudentPhotoUrl } from "../lib/api";

// Color palette for initials-based fallback avatars
const AVATAR_COLORS = [
  "bg-rose-500", "bg-blue-500", "bg-emerald-500", "bg-amber-500",
  "bg-violet-500", "bg-cyan-500", "bg-pink-500", "bg-teal-500",
  "bg-indigo-500", "bg-orange-500", "bg-lime-500", "bg-fuchsia-500",
];

function getColorForName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return (name[0] || "?").toUpperCase();
}

interface StudentAvatarProps {
  name: string;
  photoId?: number;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const sizeMap = {
  sm: "w-8 h-8 text-xs",
  md: "w-10 h-10 text-sm",
  lg: "w-14 h-14 text-lg",
  xl: "w-20 h-20 text-2xl",
};

export default function StudentAvatar({ name, photoId, size = "md", className = "" }: StudentAvatarProps) {
  const sizeClasses = sizeMap[size];
  const initials = getInitials(name);
  const bgColor = getColorForName(name);

  if (photoId) {
    return (
      <div className={`${sizeClasses} rounded-full overflow-hidden flex-shrink-0 ${className}`}>
        <img
          src={getStudentPhotoUrl(photoId)}
          alt={name}
          className="w-full h-full object-cover"
          onError={(e) => {
            // Fallback to initials if image fails to load
            const target = e.currentTarget;
            target.style.display = "none";
            const parent = target.parentElement;
            if (parent) {
              parent.classList.add(bgColor, "flex", "items-center", "justify-center");
              const span = document.createElement("span");
              span.className = "font-bold text-white";
              span.textContent = initials;
              parent.appendChild(span);
            }
          }}
        />
      </div>
    );
  }

  return (
    <div
      className={`${sizeClasses} ${bgColor} rounded-full flex items-center justify-center flex-shrink-0 ${className}`}
    >
      <span className="font-bold text-white">{initials}</span>
    </div>
  );
}
