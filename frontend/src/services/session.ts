/**
 * Session ของผู้ใช้ที่ล็อกอิน — ข้อมูลผู้ใช้ + access token (JWT แบบ stateless) ใน localStorage
 * ใช้ร่วมกันโดย AuthContext, api.ts และ telemetryStream.ts
 */
export const AUTH_STORAGE_KEY = 'pdm_auth_user';
export const TOKEN_KEY = 'pdm_access_token';

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);

/** ออกจากระบบ = ลบข้อมูลผู้ใช้และ token ออกจาก localStorage */
export const clearSession = () => {
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem(TOKEN_KEY);
};

/** token หมดอายุ/ไม่ถูกต้อง (HTTP 401 หรือ WebSocket ปิดด้วย 4401) → ล้าง session แล้วโหลดหน้า login ใหม่ */
export const endSession = () => {
  clearSession();
  if (window.location.pathname !== '/login') window.location.assign('/login');
};
