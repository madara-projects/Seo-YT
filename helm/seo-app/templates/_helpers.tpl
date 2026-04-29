{{- define "seo-app.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "seo-app.labels" -}}
app: {{ include "seo-app.name" . }}
app.kubernetes.io/name: {{ include "seo-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}

{{- define "seo-app.selectorLabels" -}}
app: {{ include "seo-app.name" . }}
{{- end -}}
