import type { ReactNode } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { getMetricsSummary } from "../api/metrics";
import { QUOTE_STATUSES, SERVICES, type DailyCount, type MetricsSummary } from "../api/types";
import { ErrorState, LoadingState } from "../components/States";
import { SERVICE_LABELS, STATUS_LABELS, formatDate, formatShortDate } from "../lib/format";
import { useFocusOnMount, usePageTitle } from "../lib/hooks";
import { cardClass, linkClass } from "../lib/ui";
import { useRequest } from "../lib/useRequest";

/*
  Tablero de métricas. Las gráficas están hechas a mano (SVG y divs de Tailwind, sin librerías):
  cada una va en un <figure> con un resumen en texto y una tabla con los mismos datos, así la
  información no depende de ver la gráfica (lectores de pantalla, daltonismo, impresión).
*/

export function DashboardPage() {
  usePageTitle("Dashboard");
  const { data, error, loading, retry } = useRequest(getMetricsSummary, "metrics");

  let content: ReactNode;
  if (loading) {
    content = <LoadingState label="Loading metrics…" />;
  } else if (error || !data) {
    content = (
      <ErrorState
        title="Couldn't load the metrics"
        message={error instanceof ApiError ? error.message : "Something went wrong."}
        onRetry={retry}
      />
    );
  } else {
    content = <Dashboard metrics={data} />;
  }

  return content;
}

function Dashboard({ metrics }: { metrics: MetricsSummary }) {
  const headingRef = useFocusOnMount<HTMLHeadingElement>();
  const last30 = metrics.last_30_days.reduce((sum, day) => sum + day.count, 0);

  return (
    <div className="space-y-6">
      <h1 ref={headingRef} tabIndex={-1} className="font-display text-2xl font-bold text-ink-900 sm:text-3xl">
        Dashboard
      </h1>

      {/* <dl>: cada tile es un par "nombre → valor" */}
      <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Total quotes" value={metrics.total} />
        <StatTile label="New (awaiting reply)" value={metrics.by_status.new} href="/quotes?status=new" />
        <StatTile label="Last 30 days" value={last30} />
        <StatTile label="Scheduled" value={metrics.by_status.scheduled} href="/quotes?status=scheduled" />
      </dl>

      <DailyChart days={metrics.last_30_days} total={last30} />

      <div className="grid gap-6 lg:grid-cols-2">
        <BarList
          title="Quotes by status"
          firstColumn="Status"
          total={metrics.total}
          // Orden fijo del flujo de trabajo (new → closed), no por cantidad
          rows={QUOTE_STATUSES.map((status) => ({
            key: status,
            label: STATUS_LABELS[status],
            value: metrics.by_status[status] ?? 0,
            href: `/quotes?status=${status}`,
          }))}
        />
        <BarList
          title="Quotes by service"
          firstColumn="Service"
          total={metrics.total}
          // De mayor a menor: así se compara más fácil
          rows={SERVICES.map((service) => ({
            key: service,
            label: SERVICE_LABELS[service],
            value: metrics.by_service[service] ?? 0,
          })).sort((a, b) => b.value - a.value)}
        />
      </div>
    </div>
  );
}

function StatTile({ label, value, href }: { label: string; value: number; href?: string }) {
  return (
    <div className={`${cardClass} p-4`}>
      <dt className="text-sm font-medium text-ink-600">{label}</dt>
      <dd className="mt-1 font-display text-3xl font-bold text-ink-900 tabular-nums">{value.toLocaleString("en-US")}</dd>
      {href && (
        <dd className="mt-1 text-sm">
          <Link to={href} className={linkClass}>
            View quotes<span className="sr-only"> ({label})</span>
          </Link>
        </dd>
      )}
    </div>
  );
}

/** Marco común: título, resumen en texto, la gráfica y la tabla desplegable con los datos. */
function ChartFigure({ title, summary, children, table }: { title: string; summary: string; children: ReactNode; table: ReactNode }) {
  return (
    <figure className={`${cardClass} p-5`}>
      <figcaption>
        <h2 className="font-display text-lg font-semibold text-ink-900">{title}</h2>
        <p className="mt-1 text-sm text-ink-600">{summary}</p>
      </figcaption>
      <div className="mt-4">{children}</div>
      <details className="mt-4 border-t border-ink-200 pt-3">
        <summary className="inline-flex min-h-11 cursor-pointer items-center font-semibold text-brand-700">
          Show data table
        </summary>
        <div className="mt-2 max-h-80 overflow-auto">{table}</div>
      </details>
    </figure>
  );
}

const thClass = "border-b border-ink-200 py-2 pr-4 text-left font-semibold text-ink-900";
const tdClass = "border-b border-ink-100 py-1.5 pr-4 text-ink-700";

/** Tope "redondo" del eje Y (par, mínimo 2): con 0, 1 y la mitad hay 3 líneas de guía enteras. */
function niceMax(max: number): number {
  return Math.max(2, Math.ceil(max / 2) * 2);
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Barras verticales: cotizaciones por día en los últimos 30 días. */
function DailyChart({ days, total }: { days: DailyCount[]; total: number }) {
  const top = niceMax(Math.max(0, ...days.map((day) => day.count)));
  const busiest = days.reduce<DailyCount | null>((best, day) => (day.count > (best?.count ?? 0) ? day : best), null);
  const summary =
    busiest === null
      ? "No quotes in the last 30 days."
      : `${plural(total, "quote")} in the last 30 days. Busiest day: ${formatDate(busiest.date)} (${busiest.count}).`;

  /*
    El SVG usa unidades propias: cada día ocupa 10 de ancho y la altura va de 0 a `top`.
    preserveAspectRatio="none" lo estira para llenar el ancho y el alto del contenedor, así se
    adapta a cualquier pantalla. Los textos de los ejes van en HTML (fuera del SVG) para que no
    se deformen ni se achiquen en el celular.
  */
  const slot = 10;
  const gap = 2; // 2 unidades de separación entre barras
  const width = days.length * slot;
  /*
    Etiquetas del eje X: se cuentan hacia atrás desde hoy (el último día), cada 7 días en
    pantallas anchas y cada 14 en el celular. Así dos etiquetas siempre quedan separadas por un
    paso completo (contando desde el primer día, la del día 28 quedaba pegada a la de hoy, el 29).
    En los primeros 7 días no hay etiqueta: centrada tan a la izquierda, se saldría hacia el eje Y.
    Peor caso, 375 px de pantalla: ~280 px de gráfica, 14 días ≈ 130 px y una fecha ≈ 40 px.
  */
  const last = days.length - 1;
  const labelAt = (i: number) => (last - i) % 7 === 0 && (i === last || i >= 7);
  const onMobile = (i: number) => (last - i) % 14 === 0;

  return (
    <ChartFigure
      title="Quotes per day — last 30 days"
      summary={summary}
      table={
        <table className="w-full text-sm">
          <caption className="sr-only">Quotes per day, last 30 days</caption>
          <thead>
            <tr>
              <th scope="col" className={thClass}>Date</th>
              <th scope="col" className={`${thClass} text-right`}>Quotes</th>
            </tr>
          </thead>
          <tbody>
            {days.map((day) => (
              <tr key={day.date}>
                <th scope="row" className={`${tdClass} font-normal`}>
                  <time dateTime={day.date}>{formatDate(day.date)}</time>
                </th>
                <td className={`${tdClass} text-right tabular-nums`}>{day.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <div className="flex gap-2">
        {/* Eje Y: top, mitad y 0, alineados con las líneas de guía */}
        <div aria-hidden="true" className="flex h-48 flex-col justify-between text-right text-xs text-ink-500 tabular-nums">
          <span className="-translate-y-1/2">{top}</span>
          <span>{top / 2}</span>
          <span className="translate-y-1/2">0</span>
        </div>
        <div className="min-w-0 flex-1">
          {/* aria-hidden: la gráfica es visual; el resumen y la tabla dan los mismos datos */}
          <svg
            aria-hidden="true"
            viewBox={`0 0 ${width} ${top}`}
            preserveAspectRatio="none"
            className="block h-48 w-full overflow-visible"
          >
            {[0, top / 2, top].map((value) => (
              // non-scaling-stroke: la línea mide 1px aunque el SVG se estire
              <line
                key={value}
                x1={0}
                x2={width}
                y1={top - value}
                y2={top - value}
                className={value === 0 ? "stroke-ink-300" : "stroke-ink-200"}
                strokeDasharray={value === 0 ? undefined : "4 4"}
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {days.map((day, i) => (
              // group: el área de hover es toda la columna del día (más fácil de apuntar que la barra)
              <g key={day.date} className="group">
                <title>{`${formatDate(day.date)}: ${plural(day.count, "quote")}`}</title>
                <rect x={i * slot} y={0} width={slot} height={top} className="fill-transparent" />
                <rect
                  x={i * slot + gap / 2}
                  y={top - day.count}
                  width={slot - gap}
                  height={day.count}
                  className="fill-brand-600 group-hover:fill-brand-800"
                />
              </g>
            ))}
          </svg>
          {/* Eje X: cada etiqueta se ubica en % del ancho, igual que su barra */}
          <div aria-hidden="true" className="relative mt-1 h-5 text-xs text-ink-500">
            {days.map((day, i) =>
              labelAt(i) ? (
                <span
                  key={day.date}
                  // Hoy va pegada al borde derecho (no se sale de la gráfica); las demás, centradas en su barra
                  style={i === last ? { right: 0 } : { left: `${((i + 0.5) / days.length) * 100}%` }}
                  className={`absolute whitespace-nowrap ${i === last ? "" : "-translate-x-1/2"} ${
                    onMobile(i) ? "" : "hidden sm:inline"
                  }`}
                >
                  {formatShortDate(day.date)}
                </span>
              ) : null,
            )}
          </div>
        </div>
      </div>
    </ChartFigure>
  );
}

interface BarRow {
  key: string;
  label: string;
  value: number;
  href?: string;
}

/** Barras horizontales con divs: el nombre y el número siempre están escritos, la barra solo ayuda a comparar. */
function BarList({ title, firstColumn, rows, total }: { title: string; firstColumn: string; rows: BarRow[]; total: number }) {
  const max = Math.max(1, ...rows.map((row) => row.value));
  const percent = (value: number) => (total === 0 ? 0 : Math.round((value / total) * 100));
  const leader = [...rows].sort((a, b) => b.value - a.value)[0];
  const summary =
    total === 0 || !leader ? "No quotes yet." : `${plural(total, "quote")} in total. Most: ${leader.label} (${leader.value}, ${percent(leader.value)}%).`;

  return (
    <ChartFigure
      title={title}
      summary={summary}
      table={
        <table className="w-full text-sm">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr>
              <th scope="col" className={thClass}>{firstColumn}</th>
              <th scope="col" className={`${thClass} text-right`}>Quotes</th>
              <th scope="col" className={`${thClass} text-right`}>Share</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row" className={`${tdClass} font-normal`}>{row.label}</th>
                <td className={`${tdClass} text-right tabular-nums`}>{row.value}</td>
                <td className={`${tdClass} text-right tabular-nums`}>{percent(row.value)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={row.key} title={`${row.label}: ${plural(row.value, "quote")} (${percent(row.value)}%)`}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              {row.href ? (
                <Link to={row.href} className={linkClass}>
                  {row.label}
                </Link>
              ) : (
                <span className="font-medium text-ink-900">{row.label}</span>
              )}
              <span className="text-ink-600 tabular-nums">
                <strong className="text-ink-900">{row.value}</strong> · {percent(row.value)}%
              </span>
            </div>
            <div aria-hidden="true" className="mt-1 h-2 rounded-full bg-ink-100">
              {/* min-w: un valor > 0 nunca se ve como vacío */}
              <div
                className={`h-2 rounded-full bg-brand-600 ${row.value > 0 ? "min-w-1" : ""}`}
                style={{ width: `${(row.value / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </ChartFigure>
  );
}
