"use client";

import { ExternalLink, ImageOff, ImagePlus, Package, Plus, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { ErrorNotice } from "@/components/notices";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useProducts } from "@/hooks/use-nexus";
import { api, ApiError } from "@/lib/api";
import type { Product } from "@/lib/types";
import { cn } from "@/lib/utils";

const NEW = "new";

/** The products shown on the public /shop page, which the voice assistant also knows. */
export function ProductsView() {
  const list = useProducts();
  const products = list.data?.items ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = products.find((p) => p.id === selectedId) ?? null;
  const showEditor = selectedId === NEW || selected !== null;

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Products"
        description="Shown on your public shop page. The voice assistant answers from them."
        className={cn(showEditor && "hidden md:flex")}
        actions={
          <>
            <Button
              size="sm"
              variant="outline"
              nativeButton={false}
              render={<a href="/shop" target="_blank" rel="noreferrer" />}
            >
              <ExternalLink />
              Open shop page
            </Button>
            <Button size="sm" onClick={() => setSelectedId(NEW)}>
              <Plus />
              New product
            </Button>
          </>
        }
      />

      <div className="flex min-h-0 flex-1">
        <section
          aria-label="Products"
          className={cn("w-full shrink-0 flex-col border-r md:flex md:w-80 lg:w-96", showEditor ? "hidden" : "flex")}
        >
          {list.error ? (
            <div className="p-3">
              <ErrorNotice error={list.error} onRetry={() => list.mutate()} />
            </div>
          ) : list.isLoading ? (
            <div className="space-y-3 p-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="px-6 py-10 text-center text-[13px] text-muted-foreground">
              <Package className="mx-auto mb-2 size-6" strokeWidth={1.5} />
              No products yet.
              <div className="mt-3">
                <Button size="sm" onClick={() => setSelectedId(NEW)}>
                  <Plus />
                  Add the first product
                </Button>
              </div>
            </div>
          ) : (
            <ul className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
              {products.map((product) => (
                <li key={product.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(product.id)}
                    aria-current={product.id === selectedId ? "true" : undefined}
                    className={cn(
                      "relative flex w-full items-center gap-3 border-b px-3 py-2.5 text-left outline-none transition-colors focus-visible:bg-muted/70",
                      product.id === selectedId ? "bg-accent" : "hover:bg-muted/60",
                    )}
                  >
                    {product.id === selectedId && (
                      <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-brand" />
                    )}
                    <Thumb product={product} className="size-11" />
                    <span className="min-w-0 flex-1">
                      <span dir="auto" className="block truncate text-[13px] font-medium">
                        {product.name}
                      </span>
                      <span className="mt-0.5 flex items-center gap-2 text-[12px] text-muted-foreground">
                        <span className="tabular-nums">{priceText(product) || "No price"}</span>
                        {!product.is_active && (
                          <span className="rounded-full bg-muted px-1.5 py-px text-[10px] font-medium uppercase">
                            Hidden
                          </span>
                        )}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Editor" className={cn("min-w-0 flex-1 md:block", showEditor ? "block" : "hidden")}>
          {showEditor ? (
            <ProductEditor
              key={selectedId}
              product={selectedId === NEW ? null : selected}
              onClose={() => setSelectedId(null)}
              onSaved={async (saved) => {
                await list.mutate();
                setSelectedId(saved.id);
              }}
              onDeleted={async () => {
                await list.mutate();
                setSelectedId(null);
              }}
            />
          ) : (
            <Guide />
          )}
        </section>
      </div>
    </div>
  );
}

export function priceText(product: Pick<Product, "price" | "currency">) {
  if (product.price === null) return "";
  const amount = Number(product.price);
  const shown = Number.isInteger(amount) ? amount.toString() : amount.toFixed(2);
  return `${shown} ${product.currency}`.trim();
}

function Thumb({ product, className }: { product: Product; className?: string }) {
  return product.image_path ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/api/nexus${product.image_path}`}
      alt=""
      className={cn("shrink-0 rounded-md border object-cover", className)}
    />
  ) : (
    <span className={cn("flex shrink-0 items-center justify-center rounded-md border bg-muted", className)}>
      <Package className="size-4 text-muted-foreground" strokeWidth={1.75} />
    </span>
  );
}

/** Shrinks a picked photo in the browser so uploads stay small (max 1200 px, WebP/JPEG). */
async function shrinkImage(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1200 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const webp = canvas.toDataURL("image/webp", 0.85);
  return webp.startsWith("data:image/webp") ? webp : canvas.toDataURL("image/jpeg", 0.85);
}

function ProductEditor({
  product,
  onClose,
  onSaved,
  onDeleted,
}: {
  product: Product | null;
  onClose: () => void;
  onSaved: (product: Product) => Promise<void>;
  onDeleted: () => Promise<void>;
}) {
  const [name, setName] = useState(product?.name ?? "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [category, setCategory] = useState(product?.category ?? "");
  const [price, setPrice] = useState(product?.price ? String(Number(product.price)) : "");
  const [currency, setCurrency] = useState(product?.currency ?? "JOD");
  const [active, setActive] = useState(product?.is_active ?? true);
  const [order, setOrder] = useState(String(product?.sort_order ?? 0));
  const [newImage, setNewImage] = useState<string | null>(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const priceValid = price.trim() === "" || /^\d{1,10}(\.\d{1,2})?$/.test(price.trim());
  const canSave = name.trim().length > 0 && priceValid && !busy;
  const preview = newImage ?? (removeImage || !product?.image_path ? null : `/api/nexus${product.image_path}`);

  async function pick(file: File | undefined) {
    if (!file) return;
    try {
      setNewImage(await shrinkImage(file));
      setRemoveImage(false);
    } catch {
      toast.error("That file could not be read as an image.");
    }
  }

  async function save() {
    if (!canSave) return;
    setBusy(true);
    try {
      const body = JSON.stringify({
        name,
        description,
        category,
        price: price.trim() === "" ? null : price.trim(),
        currency: currency.trim() || "JOD",
        is_active: active,
        sort_order: Number.parseInt(order, 10) || 0,
        image_data_url: newImage,
        remove_image: removeImage && !newImage,
      });
      const saved = product
        ? await api<Product>(`/api/v1/products/${product.id}`, { method: "PUT", body })
        : await api<Product>("/api/v1/products", { method: "POST", body });
      await onSaved(saved);
      toast.success(product ? "Product updated" : "Product added");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not save the product");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!product) return;
    setBusy(true);
    try {
      await api(`/api/v1/products/${product.id}`, { method: "DELETE" });
      await onDeleted();
      toast.success("Product deleted");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not delete the product");
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
      className="flex h-full flex-col"
    >
      <div className="flex h-14 shrink-0 items-center justify-between gap-2 border-b px-3 sm:px-4">
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
        <div className="flex items-center gap-2">
          {product &&
            (confirmDelete ? (
              <>
                <Button type="button" variant="destructive" size="sm" onClick={remove} disabled={busy}>
                  Delete
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
                  Keep
                </Button>
              </>
            ) : (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Delete product"
                onClick={() => setConfirmDelete(true)}
              >
                <Trash2 />
              </Button>
            ))}
          <Button type="submit" size="sm" disabled={!canSave}>
            {product ? "Save" : "Add product"}
          </Button>
        </div>
      </div>

      <div className="scroll-quiet min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto grid w-full max-w-3xl gap-5 p-4 sm:p-6 md:grid-cols-[200px_1fr]">
          <div className="space-y-2">
            <div className="flex aspect-square items-center justify-center overflow-hidden rounded-xl border bg-muted">
              {preview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={preview} alt="Product" className="size-full object-cover" />
              ) : (
                <Package className="size-8 text-muted-foreground" strokeWidth={1.25} />
              )}
            </div>
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(event) => void pick(event.target.files?.[0])}
            />
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" className="flex-1" onClick={() => fileInput.current?.click()}>
                <ImagePlus />
                {preview ? "Change" : "Add photo"}
              </Button>
              {preview && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Remove photo"
                  onClick={() => {
                    setNewImage(null);
                    setRemoveImage(true);
                  }}
                >
                  <ImageOff />
                </Button>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <Field label="Name" htmlFor="p-name">
              <Input id="p-name" dir="auto" value={name} maxLength={160} onChange={(e) => setName(e.target.value)} required />
            </Field>
            <div className="grid grid-cols-[1fr_96px] gap-3">
              <Field label="Price (leave empty to hide)" htmlFor="p-price">
                <Input
                  id="p-price"
                  inputMode="decimal"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  aria-invalid={!priceValid}
                  placeholder="e.g. 45 or 12.50"
                />
              </Field>
              <Field label="Currency" htmlFor="p-currency">
                <Input id="p-currency" value={currency} maxLength={8} onChange={(e) => setCurrency(e.target.value.toUpperCase())} />
              </Field>
            </div>
            <Field label="Category (optional)" htmlFor="p-category">
              <Input id="p-category" dir="auto" value={category} maxLength={80} onChange={(e) => setCategory(e.target.value)} />
            </Field>
            <Field label="Description" htmlFor="p-description" hint="The voice assistant reads this, so include what customers ask about: size, features, delivery.">
              <Textarea
                id="p-description"
                dir="auto"
                rows={6}
                value={description}
                maxLength={4000}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>
            <div className="grid grid-cols-[1fr_96px] items-end gap-3">
              <label className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-[13px]">
                <span>
                  <span className="block font-medium">Show on the shop page</span>
                  <span className="text-[12px] text-muted-foreground">Hidden products are also unknown to the assistant.</span>
                </span>
                <Switch checked={active} onCheckedChange={setActive} label="Show on the shop page" />
              </label>
              <Field label="Order" htmlFor="p-order">
                <Input id="p-order" inputMode="numeric" value={order} onChange={(e) => setOrder(e.target.value)} />
              </Field>
            </div>
          </div>
        </div>
      </div>
    </form>
  );
}

function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="text-[12px] font-medium text-muted-foreground">
        {label}
      </label>
      {children}
      {hint && <p className="text-[12px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Guide() {
  return (
    <div className="mx-auto max-w-xl p-6 text-[13px] leading-relaxed">
      <section className="rounded-xl border bg-card p-5">
        <h3 className="font-semibold">How the shop page works</h3>
        <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-muted-foreground">
          <li>Add products with a photo, a price and a clear description.</li>
          <li>
            They appear on the public page <code className="rounded bg-muted px-1">/shop</code>, which needs no login.
          </li>
          <li>Visitors tap the microphone and ask in Arabic. The assistant answers out loud from these products and your Knowledge Base.</li>
          <li>Hide a product to remove it from the page and from the assistant.</li>
        </ol>
      </section>
    </div>
  );
}
