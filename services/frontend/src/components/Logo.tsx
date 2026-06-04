import Image from "next/image";

const LOGO_SRC = "/02-m-pulso-transparent.png";

type LogoProps = {
  size: number;
  className?: string;
  priority?: boolean;
};

export function Logo({ size, className = "", priority = false }: LogoProps) {
  return (
    <Image
      src={LOGO_SRC}
      alt="MedFlow"
      width={size}
      height={size}
      priority={priority}
      className={`shrink-0 object-contain dark:invert ${className}`.trim()}
    />
  );
}
