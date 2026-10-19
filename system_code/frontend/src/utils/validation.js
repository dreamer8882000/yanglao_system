/**
 * 前端表单验证工具
 */

/**
 * 验证规则
 */
export const rules = {
  required: (message = '此字段为必填项') => ({
    validator: (value) => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== null && value !== undefined && String(value).trim() !== '';
    },
    message
  }),

  minLength: (min, message) => ({
    validator: (value) => String(value).length >= min,
    message: message || `最少需要 ${min} 个字符`
  }),

  maxLength: (max, message) => ({
    validator: (value) => String(value).length <= max,
    message: message || `最多允许 ${max} 个字符`
  }),

  email: (message = '邮箱格式不正确') => ({
    validator: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
    message
  }),

  phone: (message = '手机号格式不正确') => ({
    validator: (value) => /^1[3-9]\d{9}$/.test(value),
    message
  }),

  number: (message = '请输入有效的数字') => ({
    validator: (value) => !isNaN(parseFloat(value)) && isFinite(value),
    message
  }),

  integer: (message = '请输入整数') => ({
    validator: (value) => Number.isInteger(Number(value)),
    message
  }),

  range: (min, max, message) => ({
    validator: (value) => {
      const num = Number(value);
      return num >= min && num <= max;
    },
    message: message || `请输入 ${min} 到 ${max} 之间的数值`
  }),

  url: (message = 'URL 格式不正确') => ({
    validator: (value) => {
      try {
        new URL(value);
        return true;
      } catch {
        return false;
      }
    },
    message
  }),

  date: (message = '日期格式不正确') => ({
    validator: (value) => !isNaN(Date.parse(value)),
    message
  }),

  pattern: (regex, message = '格式不正确') => ({
    validator: (value) => regex.test(value),
    message
  }),

  custom: (validator, message = '验证失败') => ({
    validator,
    message
  })
};

/**
 * 表单验证器
 */
export class FormValidator {
  constructor(schema) {
    this.schema = schema;
  }

  validate(data) {
    const errors = {};
    let isValid = true;

    for (const field in this.schema) {
      const fieldRules = this.schema[field];
      const value = data[field];
      const fieldErrors = [];

      for (const rule of fieldRules) {
        if (!rule.validator(value)) {
          fieldErrors.push(rule.message);
          isValid = false;
        }
      }

      if (fieldErrors.length > 0) {
        errors[field] = fieldErrors;
      }
    }

    return { isValid, errors };
  }

  validateField(field, value) {
    const fieldRules = this.schema[field];
    if (!fieldRules) return { isValid: true, errors: [] };

    const errors = [];

    for (const rule of fieldRules) {
      if (!rule.validator(value)) {
        errors.push(rule.message);
      }
    }

    return { isValid: errors.length === 0, errors };
  }
}

/**
 * 老人档案验证规则
 */
export const elderFormRules = {
  name: [
    rules.required('姓名不能为空'),
    rules.minLength(2, '姓名至少 2 个字符'),
    rules.maxLength(20, '姓名最多 20 个字符')
  ],
  age: [
    rules.required('年龄不能为空'),
    rules.integer('年龄必须是整数'),
    rules.range(1, 150, '请输入有效的年龄')
  ],
  roomNo: [
    rules.required('房间号不能为空'),
    rules.maxLength(20, '房间号最多 20 个字符')
  ],
  admissionDate: [
    rules.required('入院日期不能为空'),
    rules.date('日期格式不正确')
  ],
  contactPhone: [
    rules.phone('手机号格式不正确')
  ]
};

/**
 * 摄像头验证规则
 */
export const cameraFormRules = {
  name: [
    rules.required('摄像头名称不能为空'),
    rules.maxLength(50, '名称最多 50 个字符')
  ],
  roomNo: [
    rules.required('房间号不能为空'),
    rules.maxLength(20, '房间号最多 20 个字符')
  ],
  streamUrl: [
    rules.custom(
      (value) => !value || value.startsWith('rtsp://') || value.startsWith('http'),
      '请输入有效的 RTSP 或 HTTP 流地址'
    )
  ]
};

/**
 * 排班验证规则
 */
export const scheduleFormRules = {
  userId: [
    rules.required('请选择值班人员')
  ],
  shiftDate: [
    rules.required('排班日期不能为空'),
    rules.date('日期格式不正确')
  ],
  shiftType: [
    rules.required('请选择班次类型')
  ],
  startTime: [
    rules.required('开始时间不能为空')
  ],
  endTime: [
    rules.required('结束时间不能为空')
  ]
};

/**
 * 快速验证函数
 */
export const validate = {
  isEmpty: (value) => {
    if (value === null || value === undefined) return true;
    if (typeof value === 'string') return value.trim() === '';
    if (Array.isArray(value)) return value.length === 0;
    return false;
  },

  isEmail: (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email),

  isPhone: (phone) => /^1[3-9]\d{9}$/.test(phone),

  isUrl: (url) => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  },

  isNumber: (value) => !isNaN(parseFloat(value)) && isFinite(value),

  isInteger: (value) => Number.isInteger(Number(value)),

  inRange: (value, min, max) => {
    const num = Number(value);
    return num >= min && num <= max;
  }
};

export default {
  rules,
  FormValidator,
  elderFormRules,
  cameraFormRules,
  scheduleFormRules,
  validate
};
