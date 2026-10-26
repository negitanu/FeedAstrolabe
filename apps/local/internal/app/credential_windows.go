//go:build windows

package app

import "errors"

func readOllamaToken() (string, error) {
	return "", errors.New("WindowsでのOllamaクラウドtoken ACL検証は未対応です")
}
