package app

import (
	"bytes"
	"golang.org/x/net/html"
	"net/url"
	"strings"
)

var readerTags = map[string]bool{"p": true, "br": true, "a": true, "strong": true, "em": true, "b": true, "i": true, "ul": true, "ol": true, "li": true, "blockquote": true, "pre": true, "code": true, "h2": true, "h3": true, "h4": true, "hr": true, "table": true, "thead": true, "tbody": true, "tr": true, "th": true, "td": true}

// SanitizeRichHTML emits an allowlist without images, active content or attributes.
func SanitizeRichHTML(raw string, base *url.URL) string {
	doc, e := html.Parse(strings.NewReader(raw))
	if e != nil {
		return ""
	}
	root := &html.Node{Type: html.ElementNode, Data: "div"}
	var walk func(*html.Node, *html.Node)
	walk = func(n, parent *html.Node) {
		if n.Type == html.TextNode {
			parent.AppendChild(&html.Node{Type: html.TextNode, Data: n.Data})
			return
		}
		if n.Type == html.ElementNode && (n.Data == "script" || n.Data == "style" || n.Data == "iframe" || n.Data == "object" || n.Data == "svg" || n.Data == "math" || n.Data == "template") {
			return
		}
		next := parent
		if n.Type == html.ElementNode && readerTags[n.Data] {
			next = &html.Node{Type: html.ElementNode, Data: n.Data, DataAtom: n.DataAtom}
			parent.AppendChild(next)
			if n.Data == "a" {
				for _, a := range n.Attr {
					if a.Key == "href" {
						if link := httpLink(a.Val, base); link != "" {
							next.Attr = append(next.Attr, html.Attribute{Key: "href", Val: link})
						}
					} else if a.Key == "title" {
						next.Attr = append(next.Attr, html.Attribute{Key: "title", Val: a.Val})
					}
				}
			}
		}
		for child := n.FirstChild; child != nil; child = child.NextSibling {
			walk(child, next)
		}
	}
	walk(doc, root)
	var out bytes.Buffer
	for child := root.FirstChild; child != nil; child = child.NextSibling {
		_ = html.Render(&out, child)
	}
	return out.String()
}
