import React, { useEffect, useState } from 'react';
import { api } from '../../services/api';

/**
 * <img> ของภาพที่ต้องล็อกอิน (ภาพใบมีด /tool-vision/inspections/{id}/blades/{b}/image)
 * <img src> ส่ง Authorization header ไม่ได้ → fetch พร้อม Bearer token แล้วแสดงจาก object URL (คืนหน่วยความจำเมื่อเลิกแสดง)
 */
export const AuthImage: React.FC<Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> & { src: string }> = ({ src, alt, ...rest }) => {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    let objectUrl: string | undefined;
    let cancelled = false;
    api
      .getBlob(src)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setUrl(undefined);
    };
  }, [src]);
  return <img src={url} alt={alt} {...rest} />;
};
